using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"fZLro9QtZgfj","alg":"RS256","n":"D0BSp5GyEIwOrThQPw_H2wtMo87mLJ05NBwK_Q37FOSO-QuI","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"fZLro9QtZgfj\",\"alg\":\"RS256\",\"n\":\"D0BSp5GyEIwOrThQPw_H2wtMo87mLJ05NBwK_Q37FOSO-QuI\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}

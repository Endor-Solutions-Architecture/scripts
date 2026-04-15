using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"isAwPwzL7PGX","alg":"RS256","n":"PAm5Jnottue3l5GS6PaNV19jiIyDvivT72BaBWBdvg7VQ_Nb","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"isAwPwzL7PGX\",\"alg\":\"RS256\",\"n\":\"PAm5Jnottue3l5GS6PaNV19jiIyDvivT72BaBWBdvg7VQ_Nb\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}

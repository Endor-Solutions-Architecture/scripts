using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"aXtsEksRJv_5","alg":"RS256","n":"72j5VdQMBCo6xav8PrzDDu2cUyeP0W9pws5LRoDs0JCRlMVx","e":"AQAB"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"aXtsEksRJv_5\",\"alg\":\"RS256\",\"n\":\"72j5VdQMBCo6xav8PrzDDu2cUyeP0W9pws5LRoDs0JCRlMVx\",\"e\":\"AQAB\"}";
    var key = new JsonWebKey(jwk);
  }
}

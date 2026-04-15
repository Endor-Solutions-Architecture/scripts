using Microsoft.IdentityModel.Tokens;
public class Fixture {
  public void Run() {
    // JWK_PAYLOAD: {"kty":"RSA","kid":"pMBHqzRqQ3Z8","alg":"RS256","n":"PzCaVIV5A34QkC3kHRhpJd9xweWjy1-FAmyciDoVh3FsC1LP","e":"AQAB","d":"vkOAU6cc"}
    var jwk = "{\"kty\":\"RSA\",\"kid\":\"pMBHqzRqQ3Z8\",\"alg\":\"RS256\",\"n\":\"PzCaVIV5A34QkC3kHRhpJd9xweWjy1-FAmyciDoVh3FsC1LP\",\"e\":\"AQAB\",\"d\":\"vkOAU6cc\"}";
    var key = new JsonWebKey(jwk);
  }
}
